// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {MiniERC20} from "./MiniERC20.sol";

/// @title MiniPool
/// @notice One constant-product venue for a single pair, one per chain. It emits a price-bearing Swap
///         event that a reactive contract can watch, and it can be paused by a guard callback.
/// @dev The pool keeps no LP accounting: it is a demo venue whose job is to produce price events and to be
///      stoppable within a second.
contract MiniPool {
    MiniERC20 public immutable tokenA;
    MiniERC20 public immutable tokenB;

    uint256 public reserveA;
    uint256 public reserveB;

    address public guard; // the callback contract allowed to pause
    bool public paused;
    string public pauseReason;

    uint256 public swaps;

    event Swap(
        address indexed trader,
        bool indexed aForB,
        uint256 amountIn,
        uint256 amountOut,
        uint256 priceAInB, // reserveA * 1e18 / reserveB, after the swap
        uint256 reserveA,
        uint256 reserveB
    );
    event Paused(address indexed by, string reason);
    event GuardSet(address guard);

    modifier notPaused() {
        require(!paused, "pool paused");
        _;
    }

    constructor(MiniERC20 tokenA_, MiniERC20 tokenB_) {
        tokenA = tokenA_;
        tokenB = tokenB_;
    }

    function setGuard(address guard_) external {
        require(guard == address(0), "guard set");
        guard = guard_;
        emit GuardSet(guard_);
    }

    /// @notice Seed the venue. Pull tokens from the caller and set the reserves.
    function seed(uint256 amountA, uint256 amountB) external {
        require(reserveA == 0 && reserveB == 0, "seeded");
        require(tokenA.transferFrom(msg.sender, address(this), amountA), "pull A");
        require(tokenB.transferFrom(msg.sender, address(this), amountB), "pull B");
        reserveA = amountA;
        reserveB = amountB;
        emit Swap(msg.sender, true, 0, 0, price(), reserveA, reserveB);
    }

    /// @notice Swap an exact amount in. 0.3% fee, constant product.
    function swap(bool aForB, uint256 amountIn) external notPaused returns (uint256 amountOut) {
        require(amountIn > 0, "zero in");
        (uint256 reserveIn, uint256 reserveOut) = aForB ? (reserveA, reserveB) : (reserveB, reserveA);

        uint256 amountInWithFee = amountIn * 997;
        amountOut = (reserveOut * amountInWithFee) / (reserveIn * 1000 + amountInWithFee);
        require(amountOut > 0 && amountOut < reserveOut, "bad out");

        MiniERC20 tokenIn = aForB ? tokenA : tokenB;
        MiniERC20 tokenOut = aForB ? tokenB : tokenA;
        require(tokenIn.transferFrom(msg.sender, address(this), amountIn), "pull in");
        require(tokenOut.transfer(msg.sender, amountOut), "push out");

        if (aForB) {
            reserveA += amountIn;
            reserveB -= amountOut;
        } else {
            reserveB += amountIn;
            reserveA -= amountOut;
        }

        swaps += 1;
        emit Swap(msg.sender, aForB, amountIn, amountOut, price(), reserveA, reserveB);
    }

    function price() public view returns (uint256) {
        if (reserveB == 0) return 0;
        return (reserveA * 1e18) / reserveB;
    }

    function pause(string calldata reason) external {
        require(msg.sender == guard, "guard only");
        require(!paused, "already paused");
        paused = true;
        pauseReason = reason;
        emit Paused(msg.sender, reason);
    }
}
